import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

export const TIER_STYLES: Record<string, string> = {
  Favorable: 'bg-teal-100 text-teal-800 border-teal-200 dark:bg-teal-900/30 dark:text-teal-300',
  Neutral:   'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300',
  Cautious:  'bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-300',
  Avoid:     'bg-rose-100 text-rose-800 border-rose-200 dark:bg-rose-900/30 dark:text-rose-300',
}

export function TierBadge({ tier }: { tier: string | null | undefined }) {
  const displayTier = tier ?? '\u2014'  // em dash for no-report state
  const style = tier
    ? (TIER_STYLES[tier] ?? 'bg-gray-100 text-gray-600 border-gray-200')
    : 'bg-slate-100 text-slate-700 border-slate-200'

  return (
    <Badge
      variant="outline"
      className={cn(
        'text-2xl font-bold px-4 py-2 border',
        style
      )}
    >
      {displayTier}
    </Badge>
  )
}
