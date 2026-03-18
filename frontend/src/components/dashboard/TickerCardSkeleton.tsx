import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

export function TickerCardSkeleton() {
  return (
    <Card className="p-4 space-y-3">
      <CardContent className="p-0 space-y-3">
        <div className="space-y-2">
          <Skeleton className="h-6 w-1/3" />
          <Skeleton className="h-4 w-2/3" />
        </div>
        <div className="flex justify-center">
          <Skeleton className="h-10 w-1/2" />
        </div>
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-3 w-1/4" />
      </CardContent>
    </Card>
  )
}
