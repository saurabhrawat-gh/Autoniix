'use client';

import * as React from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from './cn';

const E_STD:  [number, number, number, number] = [0.2,  0,   0,   1];
const E_ENTER: [number, number, number, number] = [0.12, 0,   0.1, 1];
const E_EXIT:  [number, number, number, number] = [0.33, 0,   0.2, 1];

const overlayVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.16, ease: E_STD } },
  exit: { opacity: 0, transition: { duration: 0.16, ease: E_EXIT } },
};

const contentVariants = {
  hidden: { opacity: 0, scale: 0.98, y: 12 },
  visible: { opacity: 1, scale: 1, y: 0, transition: { duration: 0.2, ease: E_ENTER } },
  exit: { opacity: 0, scale: 0.98, y: 8, transition: { duration: 0.2, ease: E_EXIT } },
};

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogPortal = DialogPrimitive.Portal;
export const DialogClose = DialogPrimitive.Close;

export const DialogOverlay = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay ref={ref} asChild {...props}>
    <motion.div
      variants={overlayVariants}
      initial="hidden"
      animate="visible"
      exit="exit"
      className={cn('fixed inset-0 z-50 bg-black/50 backdrop-blur-[2px]', className)}
    />
  </DialogPrimitive.Overlay>
));
DialogOverlay.displayName = 'DialogOverlay';

const sizeClasses = {
  sm: 'max-w-[360px]',
  md: 'max-w-[480px]',
  lg: 'max-w-[720px]',
};

export const DialogContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & {
    size?: 'sm' | 'md' | 'lg';
  }
>(({ className, children, size = 'md', ...props }, ref) => (
  <DialogPortal>
    <DialogOverlay />
    <DialogPrimitive.Content ref={ref} asChild {...props}>
      <motion.div
        variants={contentVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
        className={cn(
          'fixed left-1/2 top-1/2 z-50 flex w-full flex-col -translate-x-1/2 -translate-y-1/2 overflow-hidden',
          'bg-surface-0 border border-border rounded-xl shadow-elevated',
          'focus:outline-none',
          sizeClasses[size],
          className
        )}
      >
        {children}
      </motion.div>
    </DialogPrimitive.Content>
  </DialogPortal>
));
DialogContent.displayName = 'DialogContent';

/** Header bar with border-b separator. Put title info on the left and DialogCloseButton on the right. */
export const DialogHeader = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn('px-5 pt-5 pb-3 border-b border-border flex items-start justify-between shrink-0', className)}
    {...props}
  />
);
DialogHeader.displayName = 'DialogHeader';

/** Padded scrollable body area. Place content + DialogFooter inside. */
export const DialogBody = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('px-5 py-5 space-y-4 overflow-y-auto', className)} {...props} />
);
DialogBody.displayName = 'DialogBody';

/** Inline footer row — place inside DialogBody at the bottom of content. */
export const DialogFooter = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('flex flex-row justify-end gap-2 pt-2', className)} {...props} />
);
DialogFooter.displayName = 'DialogFooter';

/** Radix-wired close button (X icon) for use inside DialogHeader on the right side. */
export const DialogCloseButton = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Close>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Close>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Close
    ref={ref}
    className={cn(
      'shrink-0 w-7 h-7 rounded-md flex items-center justify-center',
      'text-content-tertiary hover:text-content-primary hover:bg-surface-2',
      'transition-colors duration-[120ms] focus:outline-none focus:ring-2 focus:ring-accent/40',
      'disabled:pointer-events-none',
      className
    )}
    {...props}
  >
    <X size={14} />
    <span className="sr-only">Close</span>
  </DialogPrimitive.Close>
));
DialogCloseButton.displayName = 'DialogCloseButton';

export const DialogTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn('text-base font-semibold leading-tight text-content-primary', className)}
    {...props}
  />
));
DialogTitle.displayName = 'DialogTitle';

export const DialogDescription = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Description>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description
    ref={ref}
    className={cn('text-[11px] text-content-tertiary mt-0.5', className)}
    {...props}
  />
));
DialogDescription.displayName = 'DialogDescription';
