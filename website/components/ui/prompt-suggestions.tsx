import { useState } from "react";

interface PromptSuggestionsProps {
  label: string;
  append: (message: { role: "user"; content: string }) => void;
  suggestions: string[];
}

export function PromptSuggestions({
  label,
  append,
  suggestions,
}: PromptSuggestionsProps) {
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
        messages: [{ role: "user", content: input }],
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
    <div className="space-y-6">
      <h2 className="text-center text-2xl font-bold">{label}</h2>
      <div className="flex gap-6 text-sm">
        {suggestions.map((suggestion) => (
          <button
            key={suggestion}
            onClick={(e) => {
              setInput(suggestion);
              handleSubmit(e);
            }}
            className="h-max flex-1 rounded-xl border bg-background p-4 hover:bg-muted"
          >
            <p>{suggestion}</p>
          </button>
        ))}
      </div>
    </div>
  );
}
