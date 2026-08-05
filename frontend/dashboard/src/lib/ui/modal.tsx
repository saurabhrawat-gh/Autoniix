'use client';

import * as React from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from './cn';

const E_ENTER: [number, number, number, number] = [0.12, 0, 0.1, 1];
const E_EXIT:  [number, number, number, number] = [0.33, 0, 0.2, 1];
const E_STD:   [number, number, number, number] = [0.2,  0, 0,   1];

const overlayVariants = {
  hidden:  { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.16, ease: E_STD } },
  exit:    { opacity: 0, transition: { duration: 0.16, ease: E_EXIT } },
};

const modalVariants = {
  hidden:  { opacity: 0, scale: 0.98, y: 12 },
  visible: { opacity: 1, scale: 1,    y: 0,  transition: { duration: 0.2, ease: E_ENTER } },
  exit:    { opacity: 0, scale: 0.98, y: 8,  transition: { duration: 0.2, ease: E_EXIT } },
};

const drawerVariants = {
  hidden:  { opacity: 0, x: 560 },
  visible: { opacity: 1, x: 0,   transition: { duration: 0.26, ease: E_ENTER } },
  exit:    { opacity: 0, x: 560, transition: { duration: 0.2,  ease: E_EXIT } },
};

const sizeClasses = {
  sm: 'max-w-[360px]',
  md: 'max-w-[480px]',
  lg: 'max-w-[720px]',
};

export type ModalSize = 'sm' | 'md' | 'lg' | 'drawer';

export const Modal      = DialogPrimitive.Root;
export const ModalTrigger = DialogPrimitive.Trigger;
export const ModalPortal  = DialogPrimitive.Portal;
export const ModalClose   = DialogPrimitive.Close;

export const ModalOverlay = React.forwardRef<
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
ModalOverlay.displayName = 'ModalOverlay';

export const ModalContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & {
    size?: ModalSize;
    hideClose?: boolean;
  }
>(({ className, children, size = 'md', hideClose, ...props }, ref) => {
  const isDrawer = size === 'drawer';

  return (
    <ModalPortal>
      <ModalOverlay />
      <DialogPrimitive.Content ref={ref} asChild {...props}>
        <motion.div
          variants={isDrawer ? drawerVariants : modalVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          className={cn(
            'fixed z-50 bg-surface-0 border border-border shadow-elevated focus:outline-none',
            isDrawer
              ? 'inset-y-0 right-0 w-[560px] flex flex-col rounded-l-xl'
              : [
                  'left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full rounded-xl p-6 grid gap-4',
                  sizeClasses[size],
                ],
            className
          )}
        >
          {children}
          {!hideClose && (
            <DialogPrimitive.Close
              className={cn(
                'absolute right-4 top-4 rounded-full p-1.5',
                'text-content-tertiary hover:text-content-primary hover:bg-surface-2',
                'transition-colors duration-[120ms] focus:outline-none focus:ring-2 focus:ring-accent/40',
                'disabled:pointer-events-none'
              )}
            >
              <X size={15} />
              <span className="sr-only">Close</span>
            </DialogPrimitive.Close>
          )}
        </motion.div>
      </DialogPrimitive.Content>
    </ModalPortal>
  );
});
ModalContent.displayName = 'ModalContent';

export const ModalHeader = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('flex flex-col gap-1.5 text-left', className)} {...props} />
);
ModalHeader.displayName = 'ModalHeader';

export const ModalFooter = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('flex flex-col-reverse sm:flex-row sm:justify-end sm:gap-2 gap-2', className)} {...props} />
);
ModalFooter.displayName = 'ModalFooter';

export const ModalTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn('text-lg font-semibold leading-tight tracking-tight text-content-primary', className)}
    {...props}
  />
));
ModalTitle.displayName = 'ModalTitle';

export const ModalDescription = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Description>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description
    ref={ref}
    className={cn('text-sm text-content-tertiary', className)}
    {...props}
  />
));
ModalDescription.displayName = 'ModalDescription';
