import type { Meta, StoryObj } from '@storybook/react';
import { Search, Mail } from 'lucide-react';
import { Input } from '@/lib/ui';

const meta: Meta<typeof Input> = {
  title: 'UI/Input',
  component: Input,
  tags: ['autodocs'],
  argTypes: {
    variant: { control: 'select', options: ['form', 'search'] },
    error: { control: 'boolean' },
    disabled: { control: 'boolean' },
    placeholder: { control: 'text' },
    label: { control: 'text' },
    hint: { control: 'text' },
  },
  args: { placeholder: 'Enter value…', variant: 'form' },
};

export default meta;
type Story = StoryObj<typeof Input>;

export const Default: Story = { args: { placeholder: 'Channel name' } };

export const WithLabel: Story = {
  args: { label: 'Email address', placeholder: 'you@example.com', id: 'email' },
};

export const WithHint: Story = {
  args: { label: 'Handle', placeholder: '@techinsights', hint: 'Must be unique across all channels', id: 'handle' },
};

export const WithError: Story = {
  args: {
    label: 'API Key',
    placeholder: 'sk-…',
    error: true,
    hint: 'Invalid key format',
    id: 'api-key',
  },
};

export const SearchVariant: Story = {
  args: { variant: 'search', placeholder: 'Search channels…', leftIcon: <Search size={14} /> },
};

export const WithLeftIcon: Story = {
  args: { label: 'Email', placeholder: 'you@example.com', leftIcon: <Mail size={15} />, id: 'email-icon' },
};

export const Disabled: Story = {
  args: { label: 'Workspace ID', value: 'ws_abc123', disabled: true, id: 'ws-id', readOnly: true },
};
