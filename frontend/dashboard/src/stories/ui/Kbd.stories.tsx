import type { Meta, StoryObj } from "@storybook/react";
import { Kbd } from "@/lib/ui";

const meta: Meta<typeof Kbd> = {
  title: "UI/Kbd",
  component: Kbd,
  tags: ["autodocs"],
  parameters: { layout: "centered" },
};
export default meta;
type Story = StoryObj<typeof Kbd>;

export const SingleKey: Story = {
  args: { children: "⌘" },
};

export const LetterKey: Story = {
  args: { children: "K" },
};

export const Shortcut: Story = {
  render: () => (
    <div className="flex items-center gap-1">
      <Kbd>⌘</Kbd>
      <Kbd>K</Kbd>
    </div>
  ),
};

export const CommonShortcuts: Story = {
  render: () => (
    <div className="flex flex-col gap-3">
      {[
        { label: "Open command palette", keys: ["⌘", "K"] },
        { label: "Save", keys: ["⌘", "S"] },
        { label: "Undo", keys: ["⌘", "Z"] },
        { label: "Redo", keys: ["⌘", "⇧", "Z"] },
      ].map(({ label, keys }) => (
        <div key={label} className="flex items-center justify-between gap-8 w-56">
          <span className="text-sm text-content-secondary">{label}</span>
          <div className="flex items-center gap-1">
            {keys.map((k) => (
              <Kbd key={k}>{k}</Kbd>
            ))}
          </div>
        </div>
      ))}
    </div>
  ),
};
