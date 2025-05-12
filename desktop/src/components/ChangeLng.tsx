import React, { useState } from 'react';
import i18n from '../i18n/i18n';
import { Select } from '@blueprintjs/select';
import { MenuItem, Icon } from '@blueprintjs/core';

interface LanguageItem {
  key: 'zh' | 'en';
  label: string;
}

const items: LanguageItem[] = [
  {
    key: 'zh',
    label: '简体中文'
  },
  {
    key: 'en',
    label: 'English'
  }
];

const ChangeLng = () => {

  const [_, setUpdate] = useState(0); // 添加状态用于强制更新

  const handleItemSelect = (item: LanguageItem) => {
    console.log('Selected item:', item, 'i18n => ', i18n);
    // i18n.changeLanguage(item.key).then(() => {
    //   localStorage.setItem('locale', item.key);
    //   console.log('Language changed to:', item.key, i18n.language)
    //   setUpdate(prev => prev + 1); // 强制重新渲染
    // });
    i18n.changeLanguage(item.key);
    localStorage.setItem('locale', item.key);
  };

  return (
    <div style={{ display: 'inline-block' }}>
      <Select<LanguageItem>
        items={items}
        itemRenderer={(item: LanguageItem, itemProps: { handleClick: (event: React.MouseEvent<HTMLElement>) => void }) => {
          return (
            <MenuItem
              key={item.key}
              text={item.label}
              onClick={itemProps.handleClick}
            />
          );
        }}
        onItemSelect={handleItemSelect}
        filterable={false}
      >
        <Icon icon="translate" size={16} />
      </Select>
    </div>
  );
};

export default ChangeLng;