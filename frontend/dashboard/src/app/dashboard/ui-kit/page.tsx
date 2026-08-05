'use client';

/**
 * /dashboard/ui-kit — UI Kit preview gallery.
 *
 * Showcases every primitive from `@/lib/ui/*` in all variants.
 * Use the theme toggle in the header to verify dark/light parity.
 * Dev-only browse aid; not linked from the main nav.
 */

import { useState } from 'react';
import {
  Activity,
  Plus,
  Search,
  Settings,
  Trash2,
  AlertTriangle,
  CheckCircle2,
  Info,
  Mail,
  ChevronDown,
} from 'lucide-react';
import {
  Button,
  Input,
  Textarea,
  Label,
  Checkbox,
  RadioGroup,
  RadioGroupItem,
  Switch,
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
  SelectLabel,
  SelectGroup,
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
  Badge,
  Skeleton,
  Separator,
  Kbd,
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  Popover,
  PopoverTrigger,
  PopoverContent,
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
  TooltipProvider,
  SimpleTooltip,
} from '@/lib/ui';
import { useToast } from '@/lib/toast';

function Section({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-base font-semibold text-content-primary">{title}</h2>
        {description && <p className="text-sm text-content-tertiary mt-0.5">{description}</p>}
      </div>
      <div className="card p-5 space-y-4">{children}</div>
    </section>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[120px_1fr] items-start gap-4">
      <span className="text-xs uppercase tracking-wider text-content-tertiary pt-1.5">{label}</span>
      <div className="flex flex-wrap items-center gap-2">{children}</div>
    </div>
  );
}

export default function UIKitPage() {
  const { showToast } = useToast();
  const [check, setCheck] = useState(true);
  const [sw, setSw] = useState(true);
  const [tab, setTab] = useState('overview');
  const [radio, setRadio] = useState('a');
  const [select, setSelect] = useState('');

  return (
    <TooltipProvider delayDuration={250}>
      <div className="max-w-5xl mx-auto px-6 py-8 space-y-10">
        <header className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight">UI Kit</h1>
          <p className="text-sm text-content-tertiary">
            Preview of all primitives in <code className="font-mono text-xs px-1 py-0.5 rounded bg-surface-2">@/lib/ui</code>.
            Toggle theme from the top-right to verify dark/light parity.
          </p>
        </header>

        {/* ── Buttons ─────────────────────────────────────────── */}
        <Section title="Button" description="6 variants × 4 sizes, with leftIcon, rightIcon, loading, asChild.">
          <Row label="Variants">
            <Button variant="primary">Primary</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="tonal">Tonal</Button>
            <Button variant="destructive">Destructive</Button>
            <Button variant="outline">Outline</Button>
            <Button variant="link">Link</Button>
          </Row>
          <Row label="Sizes">
            <Button size="sm">Small</Button>
            <Button size="md">Medium</Button>
            <Button size="lg">Large</Button>
            <Button size="icon" variant="secondary"><Settings size={15} /></Button>
            <Button size="icon-sm" variant="ghost"><Trash2 size={14} /></Button>
          </Row>
          <Row label="With icons">
            <Button leftIcon={<Plus size={14} />}>Create</Button>
            <Button variant="secondary" rightIcon={<ChevronDown size={14} />}>Options</Button>
            <Button loading>Saving</Button>
            <Button disabled>Disabled</Button>
          </Row>
        </Section>

        {/* ── Inputs ──────────────────────────────────────────── */}
        <Section title="Input / Textarea / Label">
          <Row label="Basic">
            <div className="w-72 space-y-1.5">
              <Label htmlFor="email" required>Email</Label>
              <Input id="email" type="email" placeholder="you@example.com" leftIcon={<Mail size={14} />} />
            </div>
          </Row>
          <Row label="With hint">
            <div className="w-72">
              <Input placeholder="Search…" leftIcon={<Search size={14} />} hint="Type to filter results." />
            </div>
          </Row>
          <Row label="Error">
            <div className="w-72">
              <Input defaultValue="invalid" error hint="This field is required." />
            </div>
          </Row>
          <Row label="Textarea">
            <div className="w-full max-w-md">
              <Textarea placeholder="Write something…" hint="Markdown supported." />
            </div>
          </Row>
        </Section>

        {/* ── Select ──────────────────────────────────────────── */}
        <Section title="Select" description="Replaces native <select>; themed correctly in dark mode.">
          <Row label="Basic">
            <div className="w-64">
              <Select value={select} onValueChange={setSelect}>
                <SelectTrigger>
                  <SelectValue placeholder="Pick a niche" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectLabel>Channels</SelectLabel>
                    <SelectItem value="tech">Tech</SelectItem>
                    <SelectItem value="health">Health & Wellness</SelectItem>
                    <SelectItem value="finance">Finance</SelectItem>
                    <SelectItem value="education">Education</SelectItem>
                    <SelectItem value="entertainment">Entertainment</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>
          </Row>
        </Section>

        {/* ── Toggles ─────────────────────────────────────────── */}
        <Section title="Checkbox / Radio / Switch">
          <Row label="Checkbox">
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <Checkbox checked={check} onCheckedChange={(v) => setCheck(v === true)} />
              Auto-upload to YouTube
            </label>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <Checkbox disabled />
              Disabled
            </label>
          </Row>
          <Row label="Radio">
            <RadioGroup value={radio} onValueChange={setRadio} className="flex gap-4">
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <RadioGroupItem value="a" /> Long-form
              </label>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <RadioGroupItem value="b" /> Short-form
              </label>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <RadioGroupItem value="c" /> Both
              </label>
            </RadioGroup>
          </Row>
          <Row label="Switch">
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <Switch checked={sw} onCheckedChange={setSw} />
              Enable channel
            </label>
          </Row>
        </Section>

        {/* ── Card ────────────────────────────────────────────── */}
        <Section title="Card">
          <Row label="Default">
            <Card padding="md" className="w-72">
              <CardHeader>
                <CardTitle>Tech Daily</CardTitle>
                <CardDescription>Long-form • 3 videos / week</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-content-secondary">Last published 2 days ago.</p>
              </CardContent>
              <CardFooter>
                <Button size="sm" variant="secondary">View</Button>
                <Button size="sm" variant="primary">Trigger</Button>
              </CardFooter>
            </Card>
            <Card variant="elevated" padding="lg" className="w-64">
              <CardTitle>Elevated</CardTitle>
              <CardDescription className="mt-1">Higher shadow.</CardDescription>
            </Card>
            <Card variant="in-progress" padding="lg" className="w-64">
              <CardTitle>In progress</CardTitle>
              <CardDescription className="mt-1">Glowing border animation.</CardDescription>
            </Card>
          </Row>
        </Section>

        {/* ── Badges ──────────────────────────────────────────── */}
        <Section title="Badge">
          <Row label="Variants">
            <Badge>neutral</Badge>
            <Badge variant="accent">accent</Badge>
            <Badge variant="secondary">secondary</Badge>
            <Badge variant="success">success</Badge>
            <Badge variant="warning">warning</Badge>
            <Badge variant="error">error</Badge>
            <Badge variant="info">info</Badge>
            <Badge variant="outline">outline</Badge>
          </Row>
          <Row label="Type chips">
            <Badge variant="short" size="sm">SHORT</Badge>
            <Badge variant="long" size="sm">LONG</Badge>
          </Row>
        </Section>

        {/* ── Skeleton ────────────────────────────────────────── */}
        <Section title="Skeleton">
          <Row label="Loading">
            <div className="w-72 space-y-2">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-24 w-full" />
            </div>
          </Row>
        </Section>

        {/* ── Tabs ────────────────────────────────────────────── */}
        <Section title="Tabs">
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList>
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="long">Long-form</TabsTrigger>
              <TabsTrigger value="short">Short-form</TabsTrigger>
              <TabsTrigger value="settings">Settings</TabsTrigger>
            </TabsList>
            <TabsContent value="overview">
              <p className="text-sm text-content-secondary">Overview tab content.</p>
            </TabsContent>
            <TabsContent value="long">
              <p className="text-sm text-content-secondary">Long-form metrics.</p>
            </TabsContent>
            <TabsContent value="short">
              <p className="text-sm text-content-secondary">Short-form metrics.</p>
            </TabsContent>
            <TabsContent value="settings">
              <p className="text-sm text-content-secondary">Channel settings.</p>
            </TabsContent>
          </Tabs>
        </Section>

        {/* ── Dialog ──────────────────────────────────────────── */}
        <Section title="Dialog" description="Replaces ad-hoc fixed inset-0 modals.">
          <Row label="Trigger">
            <Dialog>
              <DialogTrigger asChild>
                <Button variant="destructive" leftIcon={<AlertTriangle size={14} />}>
                  Delete channel
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Delete channel?</DialogTitle>
                  <DialogDescription>
                    This action cannot be undone. All scheduled videos for this channel will be paused.
                  </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                  <Button variant="secondary">Cancel</Button>
                  <Button variant="destructive">Delete</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </Row>
        </Section>

        {/* ── Dropdown ────────────────────────────────────────── */}
        <Section title="Dropdown menu">
          <Row label="Trigger">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="secondary" rightIcon={<ChevronDown size={14} />}>
                  Actions
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start">
                <DropdownMenuLabel>Channel actions</DropdownMenuLabel>
                <DropdownMenuItem>
                  <Activity size={14} />
                  View metrics
                  <DropdownMenuShortcut>⌘M</DropdownMenuShortcut>
                </DropdownMenuItem>
                <DropdownMenuItem>
                  <Settings size={14} />
                  Settings
                  <DropdownMenuShortcut>⌘,</DropdownMenuShortcut>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem destructive>
                  <Trash2 size={14} />
                  Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </Row>
        </Section>

        {/* ── Popover ─────────────────────────────────────────── */}
        <Section title="Popover">
          <Row label="Trigger">
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="secondary">Open popover</Button>
              </PopoverTrigger>
              <PopoverContent>
                <div className="space-y-2">
                  <h4 className="text-sm font-semibold">Popover content</h4>
                  <p className="text-xs text-content-tertiary">
                    Useful for filter pickers, color choosers, or any anchored panel.
                  </p>
                  <Input placeholder="Quick search…" />
                </div>
              </PopoverContent>
            </Popover>
          </Row>
        </Section>

        {/* ── Tooltip ─────────────────────────────────────────── */}
        <Section title="Tooltip">
          <Row label="Hover">
            <SimpleTooltip content="Trigger a render">
              <Button variant="secondary" size="icon"><Plus size={15} /></Button>
            </SimpleTooltip>
            <SimpleTooltip content="Open settings" side="right">
              <Button variant="ghost" size="icon"><Settings size={15} /></Button>
            </SimpleTooltip>
            <SimpleTooltip content={<span>Press <Kbd>⌘</Kbd> <Kbd>K</Kbd></span>}>
              <Button variant="tonal">Command palette</Button>
            </SimpleTooltip>
          </Row>
        </Section>

        {/* ── Toast ───────────────────────────────────────────── */}
        <Section title="Toast" description="Existing ToastProvider — fired via showToast()">
          <Row label="Trigger">
            <Button variant="secondary" leftIcon={<CheckCircle2 size={14} />} onClick={() => showToast('Saved successfully', 'success')}>Success</Button>
            <Button variant="secondary" leftIcon={<Info size={14} />} onClick={() => showToast('Heads up — this is informational')}>Info</Button>
            <Button variant="secondary" leftIcon={<AlertTriangle size={14} />} onClick={() => showToast('Approaching budget limit', 'warning')}>Warning</Button>
            <Button variant="secondary" leftIcon={<AlertTriangle size={14} />} onClick={() => showToast('Job failed to render', 'error')}>Error</Button>
            <Button
              variant="secondary"
              onClick={() =>
                showToast('Video deleted', {
                  variant: 'success',
                  action: { label: 'Undo', onAct: () => showToast('Restored', 'success') },
                })
              }
            >
              With action
            </Button>
          </Row>
        </Section>

        {/* ── Misc ────────────────────────────────────────────── */}
        <Section title="Separator / Kbd">
          <div className="text-sm text-content-secondary">Above</div>
          <Separator />
          <div className="text-sm text-content-secondary">Below</div>
          <Row label="Keys">
            <Kbd>⌘</Kbd> <Kbd>K</Kbd>
            <span className="text-xs text-content-tertiary">— open command palette</span>
          </Row>
        </Section>
      </div>
    </TooltipProvider>
  );
}
