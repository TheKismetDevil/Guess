import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import UserAvatar from '@/components/UserAvatar.vue'
import LeaderboardRow from '@/components/LeaderboardRow.vue'
import VotingDetail from '@/components/VotingDetail.vue'

vi.mock('vue-chartjs', () => ({ Doughnut: { template: '<div />' } }))

describe('UserAvatar', () => {
  it('loads the proxied avatar by opaque key and falls back to the initial on error', async () => {
    const wrapper = mount(UserAvatar, { props: { avatarKey: 'abc123', name: 'alice' } })
    const img = wrapper.get('img')
    expect(img.attributes('src')).toBe('/api/v1/avatars/abc123')
    await img.trigger('error')
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.text()).toBe('A')
    // A new key retries the image.
    await wrapper.setProps({ avatarKey: 'def456' })
    expect(wrapper.get('img').attributes('src')).toBe('/api/v1/avatars/def456')
  })

  it('shows the initial when there is no avatar key', () => {
    const wrapper = mount(UserAvatar, { props: { avatarKey: null, name: '张三' } })
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.text()).toBe('张')
  })
})

describe('avatar usage', () => {
  it('renders the avatar in leaderboard rows', () => {
    const wrapper = mount(LeaderboardRow, {
      props: { entry: { username: 'bob', total_points: 3, races_participated: 1, avg_points: 3, avatar_key: 'k1' }, rank: 1, isCurrentUser: false, leaderGap: 0, previousGap: 0 },
      attachTo: document.createElement('tbody'),
    })
    expect(wrapper.get('.row-avatar img').attributes('src')).toBe('/api/v1/avatars/k1')
  })

  it('lists voters with avatars in the voting distribution', () => {
    const votes = [
      { user_id: 1, username: 'amy', avatar_key: 'k1', race_horse_id: 1, horse_name: '马A', created_at: '' },
      { user_id: 2, username: 'ben', avatar_key: null, race_horse_id: 1, horse_name: '马A', created_at: '' },
    ]
    const wrapper = mount(VotingDetail, { props: { votes } })
    const chips = wrapper.findAll('.voter-chip')
    expect(chips.map(c => c.text())).toEqual(['amy', 'Bben'])
    expect(chips[0]!.get('img').attributes('src')).toBe('/api/v1/avatars/k1')
    expect(wrapper.get('.legend-voters').attributes('aria-label')).toBe('投票人：amy、ben')
  })
})
