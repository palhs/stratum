import Link from 'next/link'
import { Button } from '@/components/ui/button'

export default async function ReportPage({
  params,
}: {
  params: Promise<{ symbol: string }>
}) {
  const { symbol } = await params

  return (
    <div className="min-h-screen bg-background px-6 py-6 max-w-7xl mx-auto">
      <Button variant="ghost" asChild className="mb-4">
        <Link href="/">Back to dashboard</Link>
      </Button>
      <h1 className="text-xl font-bold mb-2">{symbol.toUpperCase()}</h1>
      <p className="text-muted-foreground">Full report view coming soon.</p>
    </div>
  )
}
