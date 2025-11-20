"use client";

import { useState } from "react";
import axios from "axios";
import MessageBubble from "./MessageBubble";
import ChatInput from "./ChatInput";

export default function ChatBox() {
  const [messages, setMessages] = useState<
    { from: "user" | "bot"; text: string }[]
  >([]);

  async function sendMessage(msg: string) {
    setMessages((m) => [...m, { from: "user", text: msg }]);

    const res = await axios.post("/api/rasa", {
      sender: "user",
      message: msg,
    });

    const replies = res.data.messages;

    replies.forEach((r: any) => {
      if (r.text) {
        setMessages((m) => [...m, { from: "bot", text: r.text }]);
      }
    });
  }

  return (
    <div className="max-w-lg mx-auto border rounded-xl shadow-lg mt-10 h-[600px] flex flex-col">
      <div className="flex-1 overflow-y-auto p-4">
        {messages.map((m, i) => (
          <MessageBubble key={i} from={m.from} text={m.text} />
        ))}
      </div>

      <ChatInput onSend={sendMessage} />
    </div>
  );
}
