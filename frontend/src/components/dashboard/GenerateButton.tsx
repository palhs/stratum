import { Button } from '@/components/ui/button'

interface GenerateButtonProps {
  onClick: () => void
  disabled?: boolean
}

export function GenerateButton({ onClick, disabled = false }: GenerateButtonProps) {
  return (
    <Button
      variant="secondary"
      className="w-full min-h-[44px]"
      onClick={(e) => {
        e.preventDefault()    // prevent Link navigation
        e.stopPropagation()   // prevent event bubbling to card Link
        onClick()
      }}
      disabled={disabled}
    >
      Generate Report
    </Button>
  )
}
