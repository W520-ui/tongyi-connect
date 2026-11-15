import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { customerStrings } from '../../../i18n/customer'
import ChatComposer from '../ChatComposer.vue'

async function mountWithText(text: string) {
  const wrapper = mount(ChatComposer, { props: { strings: customerStrings['en-US'] } })
  const textarea = wrapper.get('textarea')
  await textarea.setValue(text)
  return { wrapper, textarea }
}

describe('ChatComposer', () => {
  it('sends the trimmed text on Enter and clears the input', async () => {
    const { wrapper, textarea } = await mountWithText('  Do you ship to Spain?  ')
    await textarea.trigger('keydown', { key: 'Enter' })

    expect(wrapper.emitted('send')).toEqual([['Do you ship to Spain?']])
    expect((textarea.element as HTMLTextAreaElement).value).toBe('')
  })

  it('keeps the text on Shift+Enter', async () => {
    const { wrapper, textarea } = await mountWithText('line one')
    await textarea.trigger('keydown', { key: 'Enter', shiftKey: true })

    expect(wrapper.emitted('send')).toBeUndefined()
  })

  it('does not send while an IME composition is confirming a candidate', async () => {
    const { wrapper, textarea } = await mountWithText('耳机')
    await textarea.trigger('keydown', { key: 'Enter', isComposing: true })
    await textarea.trigger('keydown', { key: 'Enter', keyCode: 229 })

    expect(wrapper.emitted('send')).toBeUndefined()
  })

  it('does not send blank text', async () => {
    const { wrapper, textarea } = await mountWithText('   ')
    await textarea.trigger('keydown', { key: 'Enter' })

    expect(wrapper.emitted('send')).toBeUndefined()
  })
})
