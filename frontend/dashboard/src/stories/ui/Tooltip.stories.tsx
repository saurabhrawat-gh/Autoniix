import type { Meta, StoryObj } from "@storybook/react";
import { SimpleTooltip, TooltipProvider, Button } from "@/lib/ui";

const meta: Meta<typeof SimpleTooltip> = {
  title: "UI/Tooltip",
  component: SimpleTooltip,
  tags: ["autodocs"],
  parameters: { layout: "centered" },
  decorators: [
    (Story) => (
      <TooltipProvider>
        <Story />
      </TooltipProvider>
    ),
  ],
};
export default meta;
type Story = StoryObj<typeof SimpleTooltip>;

export const Top: Story = {
  render: () => (
    <TooltipProvider>
      <SimpleTooltip content="Top tooltip" side="top">
        <Button variant="secondary">Hover me (top)</Button>
      </SimpleTooltip>
    </TooltipProvider>
  ),
};

export const Right: Story = {
  render: () => (
    <TooltipProvider>
      <SimpleTooltip content="Right tooltip" side="right">
        <Button variant="secondary">Hover me (right)</Button>
      </SimpleTooltip>
    </TooltipProvider>
  ),
};

export const Bottom: Story = {
  render: () => (
    <TooltipProvider>
      <SimpleTooltip content="Bottom tooltip" side="bottom">
        <Button variant="secondary">Hover me (bottom)</Button>
      </SimpleTooltip>
    </TooltipProvider>
  ),
};

export const Left: Story = {
  render: () => (
    <TooltipProvider>
      <SimpleTooltip content="Left tooltip" side="left">
        <Button variant="secondary">Hover me (left)</Button>
      </SimpleTooltip>
    </TooltipProvider>
  ),
};

export const WithRichContent: Story = {
  render: () => (
    <TooltipProvider>
      <SimpleTooltip
        content={
          <span className="flex items-center gap-1.5">
            <span>Save changes</span>
            <kbd className="text-[9px] opacity-60">⌘S</kbd>
          </span>
        }
        side="top"
      >
        <Button>Save</Button>
      </SimpleTooltip>
    </TooltipProvider>
  ),
};
