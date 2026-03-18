import { Check, Circle, Loader2, XCircle } from 'lucide-react'
import type { StepStatus } from '@/lib/types'

const STEP_LABELS: Record<string, string> = {
  macro_regime: 'Macro Analysis',
  valuation: 'Valuation',
  structure: 'Price Structure',
  conflict: 'Conflict Check',
  entry_quality: 'Entry Quality',
  grounding_check: 'Grounding',
  compose_report: 'Compose Report',
}

export const STEP_ORDER = [
  'macro_regime', 'valuation', 'structure', 'conflict',
  'entry_quality', 'grounding_check', 'compose_report',
] as const

function StepIcon({ status, label }: { status: StepStatus; label: string }) {
  switch (status) {
    case 'completed':
      return <Check className="h-4 w-4 text-teal-600 dark:text-teal-400" aria-label={`${label} \u2014 completed`} />
    case 'in_progress':
      return <Loader2 className="h-4 w-4 text-foreground animate-spin" aria-label={`${label} \u2014 in progress`} />
    case 'failed':
      return <XCircle className="h-4 w-4 text-destructive" aria-label={`${label} \u2014 failed`} />
    default:
      return <Circle className="h-4 w-4 text-muted-foreground" aria-label={`${label} \u2014 pending`} />
  }
}

export function StepList({ steps }: { steps: Map<string, StepStatus> }) {
  return (
    <ul className="space-y-2 py-1" aria-live="polite">
      {STEP_ORDER.map((node) => {
        const status = steps.get(node) ?? 'pending'
        const label = STEP_LABELS[node]
        return (
          <li key={node} className="flex items-center gap-2 text-sm">
            <StepIcon status={status} label={label} />
            <span className={status === 'completed' ? 'text-foreground' : 'text-muted-foreground'}>
              {label}
            </span>
          </li>
        )
      })}
    </ul>
  )
}
