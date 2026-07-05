import type { Meta, StoryObj } from '@storybook/react';
import { useState } from 'react';
import { MultiSelect } from '@/lib/ui';

const meta: Meta<typeof MultiSelect> = {
  title: 'UI/MultiSelect',
  component: MultiSelect,
  tags: ['autodocs'],
  parameters: { layout: 'centered' },
};
export default meta;
type Story = StoryObj<typeof MultiSelect>;

const nicheOptions = [
  { value: 'tech', label: 'Technology' },
  { value: 'gaming', label: 'Gaming' },
  { value: 'cooking', label: 'Cooking & Food' },
  { value: 'finance', label: 'Personal Finance' },
  { value: 'fitness', label: 'Health & Fitness' },
  { value: 'travel', label: 'Travel & Lifestyle' },
  { value: 'education', label: 'Education' },
  { value: 'entertainment', label: 'Entertainment' },
];

export const Empty: Story = {
  render: () => {
    const [value, setValue] = useState<string[]>([]);
    return (
      <div className="w-72">
        <MultiSelect
          options={nicheOptions}
          value={value}
          onChange={setValue}
          label="Niches"
          placeholder="Select niches…"
        />
      </div>
    );
  },
};

export const WithPreselected: Story = {
  render: () => {
    const [value, setValue] = useState<string[]>(['tech', 'gaming']);
    return (
      <div className="w-72">
        <MultiSelect
          options={nicheOptions}
          value={value}
          onChange={setValue}
          label="Content niches"
          hint="Select all that apply."
        />
      </div>
    );
  },
};

export const ErrorState: Story = {
  render: () => {
    const [value, setValue] = useState<string[]>([]);
    return (
      <div className="w-72">
        <MultiSelect
          options={nicheOptions}
          value={value}
          onChange={setValue}
          label="Niches"
          error={true}
          hint="Please select at least one niche."
        />
      </div>
    );
  },
};

export const Disabled: Story = {
  render: () => (
    <div className="w-72">
      <MultiSelect
        options={nicheOptions}
        value={['tech', 'education']}
        label="Niches (locked)"
        disabled={true}
      />
    </div>
  ),
};
