import { Button } from '@/components/ui/button'

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 space-y-4">
      {/* eslint-disable-next-line react/no-unescaped-entities */}
      <h3 className="text-xl font-bold">Couldn't load your watchlist</h3>
      <p className="text-sm text-muted-foreground">{message}</p>
      <Button onClick={onRetry}>Try again</Button>
    </div>
  )
}
