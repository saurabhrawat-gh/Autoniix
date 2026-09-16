import type { Meta, StoryObj } from "@storybook/react";
import { Checkbox } from "@/lib/ui";
import { Label } from "@/lib/ui";

const meta: Meta<typeof Checkbox> = {
  title: "UI/Checkbox",
  component: Checkbox,
  tags: ["autodocs"],
  parameters: { layout: "centered" },
};
export default meta;
type Story = StoryObj<typeof Checkbox>;

export const Unchecked: Story = {};

export const Checked: Story = {
  args: { defaultChecked: true },
};

export const Disabled: Story = {
  args: { disabled: true },
};

export const DisabledChecked: Story = {
  args: { defaultChecked: true, disabled: true },
};

export const WithLabel: Story = {
  render: () => (
    <div className="flex items-center gap-2">
      <Checkbox id="terms" />
      <Label htmlFor="terms">Accept terms and conditions</Label>
    </div>
  ),
};

export const CheckboxGroup: Story = {
  render: () => (
    <div className="flex flex-col gap-3">
      {["Enable notifications", "Auto-publish content", "Daily digest"].map((item) => (
        <div key={item} className="flex items-center gap-2">
          <Checkbox id={item} defaultChecked={item === "Enable notifications"} />
          <Label htmlFor={item}>{item}</Label>
        </div>
      ))}
    </div>
  ),
};
