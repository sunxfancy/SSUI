import { Button, Tabs, Tab, TabPanel } from "@blueprintjs/core";
import { Component, ReactNode, Children, ReactElement } from "react";
import { IconName } from "@blueprintjs/icons";

interface TopbarProps {
    children?: ReactNode;
}

export class Topbar extends Component<TopbarProps> {
    state = {
        selectedTabId: "repo"
    };

    handleTabChange = (tabId: string) => {
        this.setState({ selectedTabId: tabId });
    };

    render() {
        const { children } = this.props;
        const childrenArray = Children.toArray(children);
        const tabIds = ["repo", "package", "sort", "settings"];
        const icons: IconName[] = ["git-repo", "package", "sort", "settings"];

        return (
            <div style={{ display: "flex", flexDirection: "column", width: "100%" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "10px" }}>
                    <Tabs
                        id="topbar-tabs"
                        selectedTabId={this.state.selectedTabId}
                        onChange={this.handleTabChange}
                        animate={true}
                        renderActiveTabPanelOnly={true}
                    >
                        {tabIds.map((id, index) => (
                            <Tab
                                key={id}
                                id={id}
                                title={<Button icon={icons[index]} size='large' variant="minimal" />}
                            />
                        ))}
                    </Tabs>
                </div>
                <div>
                    {tabIds.map((id, index) => (
                        <TabPanel
                            key={id}
                            id={id}
                            selectedTabId={this.state.selectedTabId}
                            parentId="topbar-tabs"
                            panel={childrenArray[index] as ReactElement || <div></div>}
                        />
                    ))}
                </div>
            </div>
        );
    }
}
