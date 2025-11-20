interface Props {
  from: "user" | "bot";
  text: string;
}

export default function MessageBubble({ from, text }: Props) {
  return (
    <div
      className={`mb-2 flex ${
        from === "user" ? "justify-end" : "justify-start"
      }`}
    >
      <div
        className={`px-4 py-2 rounded-xl max-w-sm ${
          from === "user"
            ? "bg-blue-600 text-white"
            : "bg-gray-200 text-black"
        }`}
      >
        {text}
      </div>
    </div>
  );
}
