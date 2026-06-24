import type { Meta, StoryObj } from '@storybook/react';
import { Textarea } from '@/lib/ui';

const meta: Meta<typeof Textarea> = {
  title: 'UI/Textarea',
  component: Textarea,
  tags: ['autodocs'],
  parameters: { layout: 'centered' },
};
export default meta;
type Story = StoryObj<typeof Textarea>;

export const Default: Story = {
  args: { placeholder: 'Write something…' },
};

export const WithValue: Story = {
  args: { defaultValue: 'This is a pre-filled textarea with some content.' },
};

export const WithHint: Story = {
  args: {
    placeholder: 'Describe your channel…',
    hint: 'Keep it under 300 characters.',
  },
};

export const ErrorState: Story = {
  args: {
    placeholder: 'Required field',
    error: true,
    hint: 'This field is required.',
  },
};

export const Disabled: Story = {
  args: {
    defaultValue: 'Cannot edit this.',
    disabled: true,
  },
};

export const Tall: Story = {
  args: {
    placeholder: 'Script content goes here…',
    className: 'min-h-[180px]',
  },
};
