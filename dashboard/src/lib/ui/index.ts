// Autoniix Dashboard UI Kit — barrel
// All primitives are themed via the CSS variables defined in app/globals.css.
// They render identically in light and dark; theme is toggled by adding
// `class="dark"` on <html>.

export { cn } from './cn';

export { Button, buttonVariants, type ButtonProps } from './button';
export { Input, type InputProps } from './input';
export { FloatingInput, type FloatingInputProps } from './floating-input';
export { Textarea, type TextareaProps } from './textarea';
export { Label } from './label';
export { Checkbox } from './checkbox';
export { RadioGroup, RadioGroupItem } from './radio-group';
export { Switch } from './switch';
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
