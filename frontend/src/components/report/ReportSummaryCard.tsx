'use client'

import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { TierBadge } from '@/components/dashboard/TierBadge'
import { ChevronDown, ChevronUp } from 'lucide-react'

interface ReportSummaryCardProps {
  tier: string
  verdict: string
  macroAssessment: string
  valuationAssessment: string
  structureAssessment: string
  isExpanded: boolean
  onExpandToggle: () => void
}

export function ReportSummaryCard({
  tier,
  verdict,
  macroAssessment,
  valuationAssessment,
  structureAssessment,
  isExpanded,
  onExpandToggle,
}: ReportSummaryCardProps) {
  return (
    <Card className="p-4">
      <div className="flex flex-col gap-4">
        <TierBadge tier={tier} />
        <div className="flex flex-wrap gap-4">
          {[
            { label: 'Macro', value: macroAssessment },
            { label: 'Valuation', value: valuationAssessment },
            { label: 'Structure', value: structureAssessment },
          ].map(({ label, value }) => (
            <div key={label} className="flex items-center gap-1">
              <span className="text-sm text-muted-foreground">{label}</span>
              <span className="text-sm text-foreground">{value}</span>
            </div>
          ))}
        </div>
        <p className="text-base leading-relaxed">{verdict}</p>
        <Button
          variant="ghost"
          className="w-full"
          onClick={onExpandToggle}
          aria-expanded={isExpanded}
        >
          {isExpanded ? 'Collapse report' : 'Read full report'}
          {isExpanded ? <ChevronUp className="ml-1 h-4 w-4" /> : <ChevronDown className="ml-1 h-4 w-4" />}
        </Button>
      </div>
    </Card>
  )
}
