import type { Turn } from './chatSlice'

// Mirrors the backend's render_markdown_lite: **bold**, "* " bullets, and
// newlines are the only formatting the AI's answers ever use.
function formatAnswer(text: string) {
  const lines = text.split('\n')
  return lines.map((line, i) => {
    const withBullet = line.replace(/^\*\s+/, '• ')
    const parts = withBullet.split(/(\*\*.+?\*\*)/g)
    return (
      <span key={i}>
        {parts.map((part, j) =>
          part.startsWith('**') && part.endsWith('**') ? (
            <b key={j}>{part.slice(2, -2)}</b>
          ) : (
            part
          ),
        )}
        {i < lines.length - 1 && <br />}
      </span>
    )
  })
}

function MessageBubble({ turn }: { turn: Turn }) {
  return (
    <>
      <div className="flex flex-col items-end gap-1.5">
        {turn.image && (
          <img
            src={turn.image}
            alt="Attached to question"
            className="max-h-40 max-w-[78%] rounded-[10px] border border-line object-cover"
          />
        )}
        <div className="max-w-[78%] rounded-[14px] rounded-br-[4px] bg-primary px-4 py-2.5 text-[14.5px] leading-relaxed text-white">
          {turn.question}
        </div>
      </div>
      {turn.answer !== null && (
        <div className="flex justify-start">
          <div className="max-w-[92%] rounded-[14px] rounded-bl-[4px] border border-line bg-beige-soft px-4 py-2.5 text-[14.5px] leading-relaxed text-ink">
            <p className="m-0">
              {turn.answer
                ? formatAnswer(turn.answer)
                : "I couldn't find anything about that in GitHub, Jira, or Slack."}
            </p>
          </div>
        </div>
      )}
    </>
  )
}

export default MessageBubble
