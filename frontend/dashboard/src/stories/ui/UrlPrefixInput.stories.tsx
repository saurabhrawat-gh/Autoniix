import type { Meta, StoryObj } from '@storybook/react';
import { UrlPrefixInput } from '@/lib/ui';

const meta: Meta<typeof UrlPrefixInput> = {
  title: 'UI/UrlPrefixInput',
  component: UrlPrefixInput,
  tags: ['autodocs'],
  parameters: { layout: 'centered' },
};
export default meta;
type Story = StoryObj<typeof UrlPrefixInput>;

export const YouTubeHandle: Story = {
  args: {
    prefix: 'youtube.com/@',
    placeholder: 'my_channel',
    label: 'YouTube handle',
  },
};

export const WithHint: Story = {
  args: {
    prefix: 'youtube.com/@',
    placeholder: 'my_channel',
    label: 'YouTube handle',
    hint: 'Must match your exact YouTube channel handle.',
  },
};

export const ErrorState: Story = {
  args: {
    prefix: 'youtube.com/@',
    defaultValue: 'bad handle!',
    label: 'YouTube handle',
    error: true,
    hint: 'Handle contains invalid characters.',
  },
};

export const WithValue: Story = {
  args: {
    prefix: 'youtube.com/@',
    defaultValue: 'autoniix_official',
    label: 'YouTube handle',
    hint: 'Currently linked handle.',
  },
};

export const WebsiteUrl: Story = {
  args: {
    prefix: 'https://',
    placeholder: 'mysite.com',
    label: 'Website',
  },
};
