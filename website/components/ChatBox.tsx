

export default function ChatBox({className}: {className?: string}) {
  
  return (
    <div className={cn(className, "w-full h-full")}>
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
