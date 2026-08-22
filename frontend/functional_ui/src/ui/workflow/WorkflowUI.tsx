import { UIProvider } from "../UIProvider";
import { Workflow } from "ssui_components";
import { ViewSwitcher } from "../common/ViewSwitcher";

interface WorkflowUIProps {
    path: string;
}

const WorkflowUI: React.FC<WorkflowUIProps> = ({ path }) => {
    
    return (
        <div style={{ position: "relative" }}>
            <Workflow path={path} />
            <div
                style={{
                    position: "absolute",
                    top: 12,
                    right: 12,
                    zIndex: 200,
                }}
            >
                <ViewSwitcher path={path} currentView="workflow" />
            </div>
        </div>
    );
};

export class WorkflowUIProvider implements UIProvider {
    getName(): string {
        return 'workflow';
    }

    getUI(path: string): JSX.Element {
        return <WorkflowUI path={path} />;
    }
}

export default WorkflowUI;
