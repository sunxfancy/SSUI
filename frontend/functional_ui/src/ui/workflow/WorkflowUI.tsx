import { UIProvider } from "../UIProvider";
import { Workflow } from "ssui_components";

interface WorkflowUIProps {
    path: string;
}

const WorkflowUI: React.FC<WorkflowUIProps> = ({ path }) => {
    
    return (
        <Workflow path={path} />
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