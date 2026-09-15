import type { Meta, StoryObj } from "@storybook/react";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem, SelectGroup, SelectLabel } from "@/lib/ui";

const meta: Meta = {
  title: "UI/Select",
  tags: ["autodocs"],
};

export default meta;
type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <Select>
      <SelectTrigger className="w-64">
        <SelectValue placeholder="Select content mode…" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="short">Short-form</SelectItem>
        <SelectItem value="long">Long-form</SelectItem>
        <SelectItem value="mixed">Mixed</SelectItem>
      </SelectContent>
    </Select>
  ),
};

export const WithGroups: Story = {
  render: () => (
    <Select>
      <SelectTrigger className="w-64">
        <SelectValue placeholder="Select provider…" />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          <SelectLabel>LLM</SelectLabel>
          <SelectItem value="openai">OpenAI GPT-4o</SelectItem>
          <SelectItem value="claude">Anthropic Claude</SelectItem>
          <SelectItem value="gemini">Google Gemini</SelectItem>
        </SelectGroup>
        <SelectGroup>
          <SelectLabel>TTS</SelectLabel>
          <SelectItem value="fish">Fish Audio</SelectItem>
          <SelectItem value="elevenlabs">ElevenLabs</SelectItem>
        </SelectGroup>
      </SelectContent>
    </Select>
  ),
};

export const Disabled: Story = {
  render: () => (
    <Select disabled>
      <SelectTrigger className="w-64">
        <SelectValue placeholder="Unavailable" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="x">Option</SelectItem>
      </SelectContent>
    </Select>
  ),
};
