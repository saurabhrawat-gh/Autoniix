import type { Meta, StoryObj } from "@storybook/react";
import { RadioGroup, RadioGroupItem } from "@/lib/ui";
import { Label } from "@/lib/ui";

const meta: Meta<typeof RadioGroup> = {
  title: "UI/RadioGroup",
  component: RadioGroup,
  tags: ["autodocs"],
  parameters: { layout: "centered" },
};
export default meta;
type Story = StoryObj<typeof RadioGroup>;

export const Default: Story = {
  render: () => (
    <RadioGroup defaultValue="short">
      {["short", "long", "mixed"].map((mode) => (
        <div key={mode} className="flex items-center gap-2">
          <RadioGroupItem value={mode} id={`mode-${mode}`} />
          <Label htmlFor={`mode-${mode}`} className="capitalize">
            {mode}
          </Label>
        </div>
      ))}
    </RadioGroup>
  ),
};

export const Disabled: Story = {
  render: () => (
    <RadioGroup defaultValue="short">
      <div className="flex items-center gap-2">
        <RadioGroupItem value="short" id="d-short" />
        <Label htmlFor="d-short">Short</Label>
      </div>
      <div className="flex items-center gap-2">
        <RadioGroupItem value="long" id="d-long" disabled />
        <Label htmlFor="d-long" className="opacity-40">
          Long (unavailable)
        </Label>
      </div>
    </RadioGroup>
  ),
};

export const ContentMode: Story = {
  render: () => (
    <div className="flex flex-col gap-1">
      <Label className="mb-2">Content mode</Label>
      <RadioGroup defaultValue="long">
        {[
          { value: "short", label: "Short-form (< 60s)" },
          { value: "long", label: "Long-form (> 5 min)" },
          { value: "mixed", label: "Mixed (both formats)" },
        ].map(({ value, label }) => (
          <div key={value} className="flex items-center gap-2">
            <RadioGroupItem value={value} id={`cm-${value}`} />
            <Label htmlFor={`cm-${value}`}>{label}</Label>
          </div>
        ))}
      </RadioGroup>
    </div>
  ),
};
