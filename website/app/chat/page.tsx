"use client";

import { useEffect, useState } from "react";
import { useChat } from "@ai-sdk/react";
import { Chat } from "@/components/ui/chat";
import { cn } from "@/lib/utils";

export default function Page() {
  const { messages, append, isLoading, stop } = useChat({ api: null });
  
    const [input, setInput] = useState("");
  
    function handleSubmit(event?: { preventDefault?: () => void }) {
      // preventDefault optional
      event?.preventDefault?.();
  
      if (!input) return;
  
      append({ role: "user", content: input });
  
      fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: [...messages, { role: "user", content: input }],
        }),
      })
        .then((res) => res.json())
        .then(
          (data) =>
            data.content && append({ role: "assistant", content: data.content })
        )
        .catch((err) =>
          append({ role: "assistant", content: "Terjadi kesalahan." })
        );
  
      setInput("");
    }
  
  return (
    <div className="flex flex-col focus-visible:outline-0 overflow-hidden h-screen">
      <header className="draggable no-draggable-children sticky top-0 p-2 touch:p-2.5 flex items-center justify-between z-20 h-header-height bg-token-main-surface-primary pointer-events-none select-none [view-transition-name:var(--vt-page-header)] *:pointer-events-auto motion-safe:transition max-md:hidden thread-xl:absolute thread-xl:start-0 thread-xl:end-0 thread-xl:shadow-none! thread-xl:bg-transparent [box-shadow:var(--sharp-edge-top-shadow)] border-b">
        <h3 className="font-medium underline w-full text-center">Chatbot Hotel Bengkulu</h3>
      </header>
      <Chat
        messages={messages}
        input={input}
        handleInputChange={(e) => setInput(e.target.value)}
        handleSubmit={handleSubmit}
        isGenerating={isLoading}
        stop={stop}
        append={append}
        suggestions={[
          "Carikan hotel dekat pantai.",
          "Rekomendasikan hotel murah premium",
          "Hotel mana yang punya restoran?",
        ]}
      />
    </div>
  );
}
