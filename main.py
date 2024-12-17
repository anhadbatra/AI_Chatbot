from langchain.chains import LLMChain
from langchain.llms import OpenAI
from langchain.prompts import PromptTemplate
from langchain.agents import initialize_agent, AgentType
from flask import Flask, Response, request, jsonify
import jwt
import os
from dotenv import load_dotenv
from langchain.tools import Tool
from validation import validate_data
from config import limiter,app


load_dotenv()
# Secret key for JWT authenticatione
SECRET_KEY = os.environ.get("secret_key")

# Mock APIs for Product Catalog and Order Management
PRODUCTS = [
    {"id": 1, "name": "Laptop", "price": 1200, "stock": 5},
    {"id": 2, "name": "Smartphone", "price": 800, "stock": 10},
    {"id": 3, "name": "Headphones", "price": 200, "stock": 15},
]
ORDERS = [
    {"order_id": "ORD123", "status": "Shipped", "items": [{"name": "Laptop", "quantity": 1}]},
    {"order_id": "ORD124", "status": "Processing", "items": [{"name": "Smartphone", "quantity": 2}]},
]
USERS = [
    {
        "user_id": "USR001",
        "name": "Alice Johnson",
        "email": "alice.johnson@example.com",
        "role": "admin",  # Role can be admin, user, etc.
        "status": "Active",  # Active, Inactive, Suspended
        "purchase_history": [
            {"order_id": "ORD123", "items": [{"name": "Laptop", "quantity": 1}]},
            {"order_id": "ORD125", "items": [{"name": "Headphones", "quantity": 2}]}
        ]
    },
    {
        "user_id": "USR002",
        "name": "Bob Smith",
        "email": "bob.smith@example.com",
        "role": "user",
        "status": "Inactive",
        "purchase_history": [
            {"order_id": "ORD124", "items": [{"name": "Smartphone", "quantity": 2}]}
        ]
    }
]


# Initialize LLM
api_key = os.environ.get("OPENAI_API_KEY")
llm = OpenAI(model="gpt-3.5-turbo-instruct", temperature=0.7)

# Tool: Product Catalog API
def fetch_product_details(product_name):
    product = next((p for p in PRODUCTS if p["name"].lower() == product_name.lower()), None)
    if product:
        response = {
            "name" : product["name"],
            "price" : product["price"]
        }
        return response
    else:
        return {"error": "Unable to fetch product details"}

# Tool: Order Management API
def fetch_order_status(order_id):
    order = next((o for o in ORDERS if o["order_id"] == order_id), None)
    if order:
        return jsonify(order),200
    else:
        return {"error": "Unable to fetch order status"}
def fetch_user_status(user_id):
    user = next((o for o in USERS if o["user_id"] == user_id), None)
    if user:
        response = {
            "user_id": user["user_id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
            "status": user["status"],
            "purchase_history": user["purchase_history"]
        }
        return response
    else:
        return {"error": "Unable to fetch User status"}

def get_agent(prompt_template):
    product_tool = Tool(
        name="ProductCatalog",
        func=fetch_product_details,
        description="Fetch product details by product name",
    )
    order_tool = Tool(
        name="OrderStatus",
        func=fetch_order_status,
        description="Track order status by order ID",
    )
    user_tool = Tool(
        name="UserStatus",
        func=fetch_user_status,
        description="Track user status by user ID",
    )
    tools = [product_tool, order_tool,user_tool]

    # Initialize agent dynamically with user-provided prompt
    agent = initialize_agent(tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=True)
    return agent

# JWT Authentication
def authenticate(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        role_id = payload.get("role_id")
        return {"payload": payload, "role_id": role_id}
    except jwt.ExpiredSignatureError:
        return {"error": "Token has expired"}
    except jwt.InvalidTokenError:
        return {"error": "Invalid token"}

# Flask routes
@app.route("/chat", methods=["POST"])
@limiter.limit("5 per minute")  # Apply rate limiting
def chat():
    data = request.json

    # Validate request data
    validation_error = validate_data(data)
    if validation_error:
        return jsonify({"error": validation_error[0]}), validation_error[1]
    
    token = data.get("token")
    user_query = data.get("query")
    custom_prompt = data.get("prompt")  # Get user-defined prompt
    
    # Authenticate user
    auth_result = authenticate(token)
    if "error" in auth_result:
        return jsonify(auth_result), 401  # Unauthorized if token is invalid or expired

    # Extract role_id and validate it
    role_id = auth_result.get("role_id")
    if not role_id:
        return jsonify({"error": "Role ID not found in token"}), 403  # Forbidden

    # Restrict access based on role_id
    if role_id == 2:
        # Role 2 has access to user-related data
        if "user_status" in user_query.lower():
            agent = get_agent(custom_prompt)
            response = agent.run(user_query)
            return jsonify({"response": response})
        else:
            return jsonify({"error": "Role 2 can only query user data"}), 403  # Forbidden
    else:
        # Other roles can perform general actions
        agent = get_agent(custom_prompt)
        response = agent.run(user_query)
        return jsonify({"response": response})


@app.route("/generate-token", methods=["POST"])
@limiter.limit("100 per minute")
def generate_token():
    data = request.json
    user_id = data.get("user_id")
    role_id = data.get("role_id")
    
    # Generate JWT token
    token = jwt.encode({"user_id": user_id,"role_id":role_id}, SECRET_KEY, algorithm="HS256")
    return jsonify({"token": token})

# Run Flask app
if __name__ == "__main__":
    app.run(port=5000,debug=True)
