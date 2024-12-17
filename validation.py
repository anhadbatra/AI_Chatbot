import re
def validate_data(data):
    if not data:
        return {"error":"Data Not found "},400
    token = data.get("token")
    user_query = data.get("query")
    custom_prompt = data.get("prompt")
    if not token:
        return {"error":"Invalid Token"},400
    if not user_query or len(user_query) > 1000:
        return{"error":"Invalid User Query"},400
    if custom_prompt and not re.match(r"^[a-zA-Z0-9\s.,!?'-]*$", custom_prompt):
        return {"error":"Custom prompts contain invalid characters"},400
    return None
