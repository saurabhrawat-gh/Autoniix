'use client';

/**
 * FloatingInput — outlined input with an animated floating label.
 *
 * The label starts inside the input field (acting as placeholder) and rises
 * above the border when the field is focused or has a value.
 *
 * Usage:
 *   <FloatingInput id="email" label="Email address" type="email" />
 *
 * All native <input> attributes are forwarded. Use `error` for error state,
 * `hint` for helper/error text below the field.
 */
import * as React from 'react';
import { cn } from './cn';

export interface FloatingInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: boolean;
  hint?: React.ReactNode;
  rightSlot?: React.ReactNode;
  containerClassName?: string;
}

export const FloatingInput = React.forwardRef<HTMLInputElement, FloatingInputProps>(
  (
    {
      id,
      label,
      error = false,
      hint,
      rightSlot,
      containerClassName,
      className,
      value,
      defaultValue,
      onFocus,
      onBlur,
      ...props
    },
    ref,
  ) => {
    const generatedId = React.useId();
    const inputId = id ?? generatedId;

    const [focused, setFocused] = React.useState(false);
    const [hasValue, setHasValue] = React.useState(
      Boolean(value ?? defaultValue),
    );

    const isFloating = focused || hasValue;

    const handleFocus = (e: React.FocusEvent<HTMLInputElement>) => {
      setFocused(true);
      onFocus?.(e);
    };

    const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
      setFocused(false);
      setHasValue(Boolean(e.target.value));
      onBlur?.(e);
    };

    React.useEffect(() => {
      setHasValue(Boolean(value));
    }, [value]);

    return (
      <div className={cn('relative w-full', containerClassName)}>
        <input
          ref={ref}
          id={inputId}
          value={value}
          defaultValue={defaultValue}
          onFocus={handleFocus}
          onBlur={handleBlur}
          placeholder=" "
          className={cn(
            'peer w-full bg-surface-0 border rounded-md',
            'px-3.5 pt-5 pb-2 text-sm text-content-primary',
            'transition-[border-color,box-shadow] duration-[120ms] ease-[cubic-bezier(0.2,0,0,1)]',
            'focus:outline-none focus:ring-2',
            error
              ? 'border-status-error focus:border-status-error focus:ring-status-error/15'
              : 'border-border hover:border-border-hover focus:border-accent focus:ring-accent/10',
            rightSlot && 'pr-9',
            className,
          )}
          {...props}
        />

        <label
          htmlFor={inputId}
          className={cn(
            'absolute left-3.5 pointer-events-none select-none',
            'transition-all duration-[120ms] ease-[cubic-bezier(0.2,0,0,1)]',
            isFloating
              ? 'top-1.5 text-[10px] font-medium tracking-wide'
              : 'top-[calc(50%-0.5em)] text-sm',
            focused
              ? error ? 'text-status-error' : 'text-accent'
              : error
                ? 'text-status-error'
                : isFloating
                  ? 'text-content-tertiary'
                  : 'text-content-secondary',
          )}
        >
          {label}
        </label>

        {rightSlot && (
          <span className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center">
            {rightSlot}
          </span>
        )}

        {hint && (
          <p className={cn('mt-1.5 text-xs', error ? 'text-status-error' : 'text-content-tertiary')}>
            {hint}
          </p>
        )}
      </div>
    );
  },
);
FloatingInput.displayName = 'FloatingInput';
