import { useAsync } from "react-use";
import { UIProvider } from '../UIProvider';
import React from 'react';
import { Label, Button, Tab, Tabs, MenuItem, Card, Elevation } from "@blueprintjs/core";
import './FunctionalUI.css';
import "normalize.css";
import "@blueprintjs/core/lib/css/blueprint.css";
import "@blueprintjs/icons/lib/css/blueprint-icons.css";
import { ItemPredicate, ItemRenderer, Select } from "@blueprintjs/select";
import { getComponentsByType } from "../../components/ComponentsManager";

interface callable {
    rank: number;
    name: string;
}

type Params = {
    params: {
        [key: string]: string;
    },
    returns: {
        [key: string]: string;
    }
}

type ScriptMeta = {
    [key: string]: Params
}

type FunctionalUIProps = {
    path: string;
};

export function FunctionalUI({ path }: FunctionalUIProps) {
    async function queryScriptMeta(): Promise<ScriptMeta> {
        let response = await fetch('/api/script?' + new URLSearchParams({
            script_path: path
        }));
        if (!response.ok) {
            throw new Error('Failed to fetch script meta');
        }
        let data = await response.json() as ScriptMeta;
        return data;
    }

    const state = useAsync(queryScriptMeta, [path]);
    const [selectedFunc, setSelectedFunc] = React.useState<callable | undefined>();

    function renderSelect(meta: ScriptMeta) {
        const first = Object.keys(meta)[0];
        const keys = Object.keys(meta).map((key, idx) => ({ name: key, rank: idx + 1 } as callable));

        const filterFunc: ItemPredicate<callable> = (query, Func, _index, exactMatch) => {
            const normalizedTitle = Func.name.toLowerCase();
            const normalizedQuery = query.toLowerCase();

            if (exactMatch) {
                return normalizedTitle === normalizedQuery;
            } else {
                return `${Func.rank}. ${normalizedTitle}`.indexOf(normalizedQuery) >= 0;
            }
        };

        const renderFunc: ItemRenderer<callable> = (Func, { handleClick, handleFocus, modifiers }) => {
            if (!modifiers.matchesPredicate) {
                return null;
            }
            return (
                <MenuItem
                    active={modifiers.active}
                    disabled={modifiers.disabled}
                    key={Func.rank}
                    onClick={handleClick}
                    onFocus={handleFocus}
                    roleStructure="listoption"
                    text={`${Func.rank}. ${Func.name}`}
                />
            );
        };

        return <Select<callable>
            items={keys}
            itemPredicate={filterFunc}
            itemRenderer={renderFunc}
            noResults={<MenuItem disabled={true} text="No results." roleStructure="listoption" />}
            onItemSelect={setSelectedFunc}
        >
            <Button className="functional-ui-select" text={selectedFunc?.name ?? first} rightIcon="double-caret-vertical" />
        </Select>
    }

    function renderInput(name: string, type: string) {
        let components = getComponentsByType(type);

        return <Tabs id={name} key={name}>
            {components.filter(c => c.port == 'input')
                .map(c => <Tab key={c.name} id={c.name} title={c.name} panel={c.component}></Tab>)}
        </Tabs>
    }

    function renderInputs(meta: Params) {
        return <div>
            {Object.entries(meta.params).map(([key, value]) =>
                <Card key={key} elevation={Elevation.TWO} className="functional-ui-card">
                    <Label className="bp5-label" >
                        {key}
                        {renderInput(key, value)}
                    </Label>
                </Card>
            )}
        </div>
    }

    function renderOutput(type: string) {
        let components = getComponentsByType(type);

        return <Tabs id="outputTabs">
            {components.filter(c => c.port == 'output')
                .map(c=> <Tab key={c.name} id={c.name} title={c.name} panel={c.component}></Tab>)}
        </Tabs>
    }

    function renderOutputs(meta: Params) {
        return <div>
            {Object.entries(meta.returns).map(([key, value]) =>
                <Card key={key} elevation={Elevation.TWO} className="functional-ui-card">
                    {renderOutput(value)}
                </Card>
            )}
        </div>
    }

    function run(event: React.MouseEvent<HTMLElement, MouseEvent>) {
        console.log('Run');
    }

    function render(meta: ScriptMeta) {
        let selected = selectedFunc?.name ?? Object.keys(meta)[0];

        return <div>
            {renderSelect(meta)}
            <div className="functional-ui-container">
                <div className="functional-ui-input">
                    Input
                    {renderInputs(meta[selected])}
                </div>
                <div className="functional-ui-button">
                    <Button intent="primary" text="Run" onClick={run} />
                </div>
                <div className="functional-ui-output">
                    Output
                    {renderOutputs(meta[selected])}
                </div>
            </div>
        </div>

    }

    return <div className='functional-ui-root'>
        <h1>Functional UI</h1>
        <p>Path: {path}</p>

        {state.loading ? <p>Loading...</p> :
            state.error ? <p>Error: {state.error.message}</p> :
                <div>
                    {render(state.value ?? {})}
                </div>}
    </div>
}


export class FunctionalUIProvider implements UIProvider {
    getName(): string {
        return 'functional';
    }

    getUI(path: string): JSX.Element {
        return <FunctionalUI path={path} />;
    }
}