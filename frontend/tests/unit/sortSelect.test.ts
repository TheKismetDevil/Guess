import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { defineComponent, ref } from 'vue'
import SortSelect from '@/components/LeaderboardSortSelect.vue'
import type { LeaderboardSort } from '@/types/leaderboard'

function mountSelect() {
  return mount(defineComponent({
    components: { SortSelect },
    setup: () => ({ value: ref<LeaderboardSort>('total_points') }),
    template: '<SortSelect v-model="value" /><output>{{ value }}</output>',
  }), { attachTo: document.body })
}

describe('ranking sort menu DOM interactions', () => {
  it('opens a custom menu, selects average, updates v-model and displays the selected check', async () => {
    const wrapper = mountSelect()
    expect(wrapper.find('select').exists()).toBe(false)
    await wrapper.get('[role="combobox"]').trigger('click')
    expect(wrapper.get('[role="combobox"]').attributes('aria-expanded')).toBe('true')
    await wrapper.findAll('[role="option"]')[1]!.trigger('click')
    expect(wrapper.get('output').text()).toBe('avg_points')
    expect(wrapper.get('[role="combobox"]').text()).toContain('按场均排行')
    await wrapper.get('[role="combobox"]').trigger('click')
    const selected = wrapper.get('[aria-selected="true"]')
    expect(selected.text()).toBe('按场均排行')
    expect(selected.find('.sort-check').exists()).toBe(true)
  })

  it('uses real DOM keyboard events and restores focus to the trigger', async () => {
    const wrapper = mountSelect()
    const trigger = wrapper.get<HTMLButtonElement>('[role="combobox"]')
    trigger.element.focus()
    await trigger.trigger('keydown', { key: 'ArrowDown' })
    await trigger.trigger('keydown', { key: 'End' })
    const active = document.getElementById(trigger.attributes('aria-activedescendant')!)
    expect(active?.textContent).toBe('按场均排行')
    await trigger.trigger('keydown', { key: 'Enter' })
    expect(wrapper.get('output').text()).toBe('avg_points')
    expect(document.activeElement).toBe(trigger.element)
  })

  it('Escape, Tab, leaving focus and outside pointer events close without changing the sort', async () => {
    const wrapper = mountSelect()
    const trigger = wrapper.get('[role="combobox"]')
    for (const key of ['Escape', 'Tab']) {
      await trigger.trigger('click')
      await trigger.trigger('keydown', { key })
      expect(trigger.attributes('aria-expanded')).toBe('false')
    }
    await trigger.trigger('click')
    document.body.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }))
    await wrapper.vm.$nextTick()
    expect(trigger.attributes('aria-expanded')).toBe('false')
    await trigger.trigger('click')
    await wrapper.findComponent(SortSelect).trigger('focusout', { relatedTarget: document.body })
    expect(trigger.attributes('aria-expanded')).toBe('false')
    expect(wrapper.get('output').text()).toBe('total_points')
  })

  it('does not treat an inside pointer press as click-outside', async () => {
    const wrapper = mountSelect()
    const trigger = wrapper.get('[role="combobox"]')
    await trigger.trigger('click')
    await wrapper.findAll('[role="option"]')[1]!.trigger('pointerdown')
    expect(trigger.attributes('aria-expanded')).toBe('true')
    await wrapper.findAll('[role="option"]')[1]!.trigger('click')
    expect(wrapper.get('output').text()).toBe('avg_points')
  })
})
