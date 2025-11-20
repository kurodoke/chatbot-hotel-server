import { NextResponse } from "next/server";
import axios from "axios";

export async function POST(req: Request) {
  const body = await req.json();
  const { sender, message } = body;

  try {
    const rasaResponse = await axios.post(
      "http://localhost:5005/webhooks/rest/webhook",
      {
        sender,
        message,
      }
    );

    return NextResponse.json({
      messages: rasaResponse.data,
    });
  } catch (error: any) {
    console.error("Error contacting Rasa:", error.message);

    return NextResponse.json(
      {
        error: "Failed to reach Rasa server",
      },
      { status: 500 }
    );
  }
}
