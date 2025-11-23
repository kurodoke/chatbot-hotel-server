from flask import Flask, request, jsonify
import google.genai as genai

app = Flask(__name__)
client = genai.Client(api_key="AIzaSyCI2b5RwBtkjl8HqZY7Yd6UwzbjGK2mXC8")

@app.post("/generate")
def generate():
    data = request.json
    prompt = data.get("prompt")

    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt
    )

    return jsonify({"reply": response.text})

if __name__ == "__main__":
    app.run(port=5007)
