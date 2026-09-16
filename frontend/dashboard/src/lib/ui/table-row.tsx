'use client';

import * as React from 'react';
import { cn } from './cn';

export interface TableRowProps extends React.HTMLAttributes<HTMLTableRowElement> {
  selected?: boolean;
  disabled?: boolean;
}

export const TableRow = React.forwardRef<HTMLTableRowElement, TableRowProps>(
  ({ className, selected, disabled, ...props }, ref) => (
    <tr
      ref={ref}
      className={cn(
        'h-12 border-b border-border',
        'transition-colors duration-[120ms] ease-[cubic-bezier(0.2,0,0,1)]',
        !disabled && 'hover:bg-surface-1 cursor-pointer',
        selected && 'bg-surface-1',
        disabled && 'opacity-50 cursor-not-allowed',
        className
      )}
      aria-selected={selected}
      aria-disabled={disabled}
      {...props}
    />
  )
);
TableRow.displayName = 'TableRow';

export interface TableCellProps extends React.TdHTMLAttributes<HTMLTableCellElement> {
  compact?: boolean;
}

export const TableCell = React.forwardRef<HTMLTableCellElement, TableCellProps>(
  ({ className, compact, ...props }, ref) => (
    <td
      ref={ref}
      className={cn(
        'text-sm text-content-primary align-middle',
        compact ? 'px-3 py-2' : 'px-4 py-3',
        className
      )}
      {...props}
    />
  )
);
TableCell.displayName = 'TableCell';

export interface TableHeadProps extends React.ThHTMLAttributes<HTMLTableCellElement> {}

export const TableHead = React.forwardRef<HTMLTableCellElement, TableHeadProps>(
  ({ className, ...props }, ref) => (
    <th
      ref={ref}
      className={cn(
        'h-10 px-4 text-left text-xs font-medium text-content-tertiary',
        'border-b border-border bg-surface-0',
        className
      )}
      {...props}
    />
  )
);
TableHead.displayName = 'TableHead';

export interface TableProps extends React.HTMLAttributes<HTMLTableElement> {}

export const Table = React.forwardRef<HTMLTableElement, TableProps>(
  ({ className, ...props }, ref) => (
    <div className="w-full overflow-auto">
      <table
        ref={ref}
        className={cn('w-full caption-bottom text-sm border-collapse', className)}
        {...props}
      />
    </div>
  )
);
Table.displayName = 'Table';

export const TableHeader = React.forwardRef<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
  <thead ref={ref} className={cn(className)} {...props} />
));
TableHeader.displayName = 'TableHeader';

export const TableBody = React.forwardRef<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
  <tbody ref={ref} className={cn('[&_tr:last-child]:border-0', className)} {...props} />
));
TableBody.displayName = 'TableBody';
