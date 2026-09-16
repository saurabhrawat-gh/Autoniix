import type { Meta, StoryObj } from "@storybook/react";
import { Label, Input } from "@/lib/ui";

const meta: Meta<typeof Label> = {
  title: "UI/Label",
  component: Label,
  tags: ["autodocs"],
  parameters: { layout: "centered" },
};
export default meta;
type Story = StoryObj<typeof Label>;

export const Basic: Story = {
  args: { children: "Channel name" },
};

export const Required: Story = {
  args: { children: "Handle", required: true },
};

export const LinkedToInput: Story = {
  render: () => (
    <div className="flex flex-col gap-1.5 w-64">
      <Label htmlFor="channel-name" required>
        Channel name
      </Label>
      <Input id="channel-name" placeholder="My YouTube channel" />
    </div>
  ),
};

export const DisabledField: Story = {
  render: () => (
    <div className="flex flex-col gap-1.5 w-64">
      <Label htmlFor="disabled-field">Read-only field</Label>
      <Input id="disabled-field" defaultValue="Cannot change" disabled />
    </div>
  ),
};
