import React, { useState, forwardRef, useImperativeHandle } from 'react';
import {TextArea, Tag} from '@blueprintjs/core';
import { registerComponent, ComponentRegister } from '../../ComponentsManager';
import styles from './style.module.css'

const PromptEditor = forwardRef((props, ref) => {
    const [ textContent, setTextContent ] = useState<string>('')

    useImperativeHandle(ref, () => {
        return {
            onExecute: () => {
                return { 'function': 'ssui.base.Prompt.create', 'params': { 'text': textContent } };
            }
        }
    }, [textContent])

    const removeTag = (index: number) => {
        const arr = textContent.split(',')
        arr.splice(index, 1)
        setTextContent(arr.filter(a => !!a).join(','))
    }

    return (
        <div className={styles.promptEditor}>
            <div className={styles.tagWp}>
                <div className={styles.tagTitle}>预览（共{textContent.split(',').filter((a: string) => !!a).length}条）：</div>
                {
                    textContent.split(',').filter(a => !!a).map((text, index) => (
                        <Tag className={styles.tag} round intent="primary" minimal key={index} onRemove={() => removeTag(index)}>{text}</Tag>
                    ))
                }
            </div>
            <TextArea className={styles.textarea} value={textContent} onChange={e => setTextContent(e.target.value)} />
            <div className={styles.tip}>* 请输入提示词，英文逗号隔开。</div>
        </div>
    )
});


[
    { 'name': 'PromptEditor', 'type': 'ssui.base.Prompt', 'port': 'input', 'component': PromptEditor } as ComponentRegister,
].forEach(registerComponent);


