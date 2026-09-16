import type { Meta, StoryObj } from "@storybook/react";
import { Separator } from "@/lib/ui";

const meta: Meta<typeof Separator> = {
  title: "UI/Separator",
  component: Separator,
  tags: ["autodocs"],
  parameters: { layout: "centered" },
};
export default meta;
type Story = StoryObj<typeof Separator>;

export const Horizontal: Story = {
  render: () => (
    <div className="w-64 flex flex-col gap-3">
      <p className="text-sm text-content-primary">Section above</p>
      <Separator />
      <p className="text-sm text-content-primary">Section below</p>
    </div>
  ),
};

export const Vertical: Story = {
  render: () => (
    <div className="flex items-center gap-3 h-8">
      <span className="text-sm text-content-primary">Left</span>
      <Separator orientation="vertical" />
      <span className="text-sm text-content-primary">Right</span>
    </div>
  ),
};

export const InMenu: Story = {
  render: () => (
    <div className="w-48 bg-surface-0 border border-border rounded-lg p-1.5 flex flex-col gap-0.5">
      {["Edit", "Duplicate"].map((item) => (
        <button key={item} className="text-sm px-2 py-1.5 rounded-md hover:bg-surface-1 text-left text-content-primary">
          {item}
        </button>
      ))}
      <Separator className="my-1" />
      <button className="text-sm px-2 py-1.5 rounded-md hover:bg-surface-1 text-left text-status-error">Delete</button>
    </div>
  ),
};
