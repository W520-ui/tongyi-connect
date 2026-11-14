import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AgentChatPanel from '../AgentChatPanel.vue'

const workflow = {
  reply: 'Yes, we ship to Spain.',
  merchant_summary: '客户语言：英语；意图：物流查询',
  intent: 'logistics',
  intent_label: '物流查询',
  detected_intents: ['logistics'],
  detected_intent_labels: ['物流查询'],
  task_plan: ['核对目的地与配送时效'],
  language: 'en-US',
  language_label: '英语',
  confidence: 0.94,
  product_confidence: 0,
  matched_product: '未匹配具体商品',
  matched_products: [],
  needs_human: false,
  handoff_reason: null,
  steps: ['识别语言：英语'],
  source: 'native',
}

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ status: 'ok', data: workflow }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

async function typeAndPress(keyInit: KeyboardEventInit) {
  const wrapper = mount(AgentChatPanel)
  const textarea = wrapper.get('textarea')
  await textarea.setValue('Do you ship to Spain?')
  await textarea.trigger('keydown', keyInit)
  await flushPromises()
  return wrapper
}

describe('AgentChatPanel composer', () => {
  it('sends the message on Enter and shows the reply', async () => {
    const wrapper = await typeAndPress({ key: 'Enter' })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(JSON.parse(String(init.body))).toMatchObject({ message: 'Do you ship to Spain?' })
    expect(wrapper.text()).toContain('Yes, we ship to Spain.')
  })

  it('does not send on Shift+Enter', async () => {
    await typeAndPress({ key: 'Enter', shiftKey: true })

    expect(fetchMock).not.toHaveBeenCalled()
  })

  // Known defect, fixed in frontend-plan F1: the Enter that confirms an IME
  // candidate (e.g. Chinese pinyin input) still sends the half-typed message.
  it.fails('does not send while an IME composition is in progress', async () => {
    await typeAndPress({ key: 'Enter', isComposing: true })

    expect(fetchMock).not.toHaveBeenCalled()
  })
})
