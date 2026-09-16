import type { Meta, StoryObj } from "@storybook/react";
import { Popover, PopoverTrigger, PopoverContent, Button } from "@/lib/ui";

const meta: Meta = {
  title: "UI/Popover",
  tags: ["autodocs"],
  parameters: { layout: "centered" },
};
export default meta;
type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="secondary">Open popover</Button>
      </PopoverTrigger>
      <PopoverContent>
        <p className="text-sm text-content-primary font-medium mb-1">Popover title</p>
        <p className="text-sm text-content-secondary">This is the popover body content. It can contain any elements.</p>
      </PopoverContent>
    </Popover>
  ),
};

export const AlignStart: Story = {
  render: () => (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="secondary">Align start</Button>
      </PopoverTrigger>
      <PopoverContent align="start">
        <p className="text-sm text-content-secondary">Aligned to the start of the trigger.</p>
      </PopoverContent>
    </Popover>
  ),
};

export const FilterPopover: Story = {
  render: () => (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="secondary">Filter</Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-56">
        <p className="text-xs font-medium text-content-tertiary mb-2 uppercase tracking-wider">Status</p>
        <div className="flex flex-col gap-1">
          {["Active", "Paused", "Archived"].map((s) => (
            <button key={s} className="text-sm px-2 py-1.5 rounded hover:bg-surface-1 text-left text-content-primary">
              {s}
            </button>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  ),
};
