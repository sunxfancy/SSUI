
import React from 'react';
import { UIProvider } from '../UIProvider';


type ModelManagerProps = {
    path: string;
};

export class ModelManager extends React.Component<ModelManagerProps> {
    constructor(props: ModelManagerProps) {
        super(props);
    }

    render() {
        return <div>Model Manager</div>;
    }
}


export class ModelManagerUIProvider implements UIProvider {
    getName(): string {
        return 'model-manager';
    }

    getUI(path: string): JSX.Element {
        return <ModelManager path={path} />;
    }
}