import { Skeleton } from '@/components/ui/skeleton'

export function ReportPageSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <Skeleton className="w-full h-32 rounded-lg" />
      <Skeleton className="w-full h-[260px] md:h-[400px] rounded-lg" />
      <div className="flex flex-col gap-2">
        <Skeleton className="h-11 w-full rounded" />
        <Skeleton className="h-11 w-full rounded" />
        <Skeleton className="h-11 w-full rounded" />
      </div>
    </div>
  )
}
