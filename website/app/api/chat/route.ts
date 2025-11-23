// /app/api/chat/route.ts
import { NextResponse } from "next/server";
import axios from "axios";

export async function POST(req: Request) {
  try {
    const { messages } = await req.json();
    const lastUser = messages[messages.length - 1].content;

    const rasaRes = await axios.post(
      "http://localhost:5005/webhooks/rest/webhook",
      {
        sender: "user",
        message: lastUser,
      }
    );

    const replies = rasaRes.data;
    const fullText = replies.map((r: any) => r.text).join("\n");

    // Format yang AI SDK v4 butuhkan
    return NextResponse.json({
      role: "assistant",
      content: fullText,
    });
  } catch (err: any) {
    console.error("Rasa API error:", err.message);
    return NextResponse.json(
      { role: "assistant", content: "Terjadi kesalahan saat memproses pesan." },
      { status: 500 }
    );
  }
}
