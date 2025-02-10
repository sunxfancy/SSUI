import React, { useState } from 'react';
import { Tabs, Tab } from "@blueprintjs/core";
import { Allotment } from "allotment";

function TabWindowManager() {
  const [selectedTabId, setSelectedTabId] = useState<string | number>("tab1");

  return <Allotment vertical={true}>
      <div>
        <Tabs
          id="TabsExample"
          onChange={(newTabId) => setSelectedTabId(newTabId)}
          selectedTabId={selectedTabId}
        >
          <Tab id="tab1" title="Tab 1" panel={<div>Content of Tab 1</div>} />
          <Tab id="tab2" title="Tab 2" panel={<div>Content of Tab 2</div>} />
          {/* 可以根据需要动态添加更多标签 */}
        </Tabs>
      </div>
      <div>
        <div>Additional Pane</div>
      </div>
    </Allotment>
}

export default TabWindowManager;