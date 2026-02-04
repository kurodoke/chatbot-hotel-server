from flask import Flask, request, jsonify
import google.genai as genai
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

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
