import { cn } from '@/lib/utils'

interface GradientOrbProps {
  variant: 'green' | 'purple' | 'blue'
  size?: number
  className?: string
  style?: React.CSSProperties
}

export default function GradientOrb({ variant, size = 600, className, style }: GradientOrbProps) {
  return (
    <div
      className={cn('orb', `orb-${variant}`, className)}
      style={{
        width: size,
        height: size,
        ...style,
      }}
    />
  )
}
