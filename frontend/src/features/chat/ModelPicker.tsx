import { useEffect, useRef, useState } from 'react'
import type { ModelInfo } from './chatSlice'

interface ModelPickerProps {
  models: ModelInfo[]
  selectedId: string
  onChange: (modelId: string) => void
}

function ChevronDownIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={2}
      stroke="currentColor"
      className="h-3.5 w-3.5 text-muted"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={2.25}
      stroke="currentColor"
      className="h-3.5 w-3.5 text-primary"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
    </svg>
  )
}

function ModelPicker({ models, selectedId, onChange }: ModelPickerProps) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const selected = models.find((m) => m.id === selectedId)

  useEffect(() => {
    if (!open) return
    function handleClickOutside(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('mousedown', handleClickOutside)
    window.addEventListener('keydown', handleKey)
    return () => {
      window.removeEventListener('mousedown', handleClickOutside)
      window.removeEventListener('keydown', handleKey)
    }
  }, [open])

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        title="Model used to answer questions in this chat"
        aria-haspopup="listbox"
        aria-expanded={open}
        className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-[12.5px] text-ink outline-none ${
          open ? 'border-primary bg-beige-soft' : 'border-line bg-beige-soft hover:bg-beige'
        }`}
      >
        <span>{selected?.label ?? 'Select model'}</span>
        <ChevronDownIcon />
      </button>

      {open && (
        <div
          role="listbox"
          className="absolute right-0 top-[calc(100%+6px)] z-20 w-56 overflow-hidden rounded-[10px] border border-line bg-beige-soft py-1 shadow-lg"
        >
          {models.map((m) => {
            const isSelected = m.id === selectedId
            return (
              <button
                key={m.id}
                type="button"
                role="option"
                aria-selected={isSelected}
                onClick={() => {
                  onChange(m.id)
                  setOpen(false)
                }}
                className={`flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-[13px] ${
                  isSelected ? 'bg-primary-light font-semibold text-ink' : 'text-ink hover:bg-beige'
                }`}
              >
                <span className="truncate">{m.label}</span>
                {isSelected && <CheckIcon />}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default ModelPicker
