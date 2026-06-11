// Autoniix Dashboard UI Kit — barrel
// All primitives are themed via the CSS variables defined in app/globals.css.
// They render identically in light and dark; theme is toggled by adding
// `class="dark"` on <html>.

export { cn } from './cn';

export { Button, buttonVariants, type ButtonProps } from './button';
export { UrlPrefixInput, type UrlPrefixInputProps } from './url-prefix-input';
export { MultiSelect, type MultiSelectProps, type MultiSelectOption } from './multi-select';
export { Input, type InputProps } from './input';
export { FloatingInput, type FloatingInputProps } from './floating-input';
export { Textarea, type TextareaProps } from './textarea';
export { Label } from './label';
export { Checkbox } from './checkbox';
export { RadioGroup, RadioGroupItem } from './radio-group';
export { Switch, SwitchRow, type SwitchRowProps } from './switch';
export {
  Select,
  SelectGroup,
  SelectValue,
  SelectTrigger,
  SelectContent,
  SelectLabel,
  SelectItem,
  SelectSeparator,
  SelectScrollUpButton,
  SelectScrollDownButton,
} from './select';

export {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
  cardVariants,
  type CardProps,
} from './card';
export { Badge, badgeVariants, type BadgeProps } from './badge';
export { Skeleton } from './skeleton';
export { Separator } from './separator';
export { Kbd } from './kbd';

export {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogOverlay,
  DialogPortal,
  DialogClose,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
} from './dialog';

export {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuCheckboxItem,
  DropdownMenuRadioItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuGroup,
  DropdownMenuPortal,
  DropdownMenuSub,
  DropdownMenuSubTrigger,
  DropdownMenuSubContent,
  DropdownMenuRadioGroup,
} from './dropdown-menu';

export { Popover, PopoverTrigger, PopoverContent, PopoverAnchor } from './popover';
export { Tabs, TabsList, TabsTrigger, TabsContent } from './tabs';
export {
  Tooltip,
  TooltipProvider,
  TooltipTrigger,
  TooltipContent,
  SimpleTooltip,
  type SimpleTooltipProps,
} from './tooltip';

export { Avatar, avatarVariants, type AvatarProps } from './avatar';
export { KpiCard, type KpiCardProps } from './kpi-card';
export { EmptyState, type EmptyStateProps } from './empty-state';
export { DeleteDialog, type DeleteDialogProps } from './delete-dialog';
export {
  ToastProvider,
  useToast,
  type Toast,
  type ToastVariant,
} from './toast';

export {
  Modal,
  ModalTrigger,
  ModalPortal,
  ModalClose,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalTitle,
  ModalDescription,
  type ModalSize,
} from './modal';

export {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
  type TableRowProps,
  type TableCellProps,
  type TableHeadProps,
  type TableProps,
} from './table-row';
