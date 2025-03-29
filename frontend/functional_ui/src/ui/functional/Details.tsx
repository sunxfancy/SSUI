import { useAsync } from "react-use";
import { Section, SectionCard } from "@blueprintjs/core";
import '../../controlers/InternalControlers'; // Register controlers
import { ControlerRef } from "../../controlers/ControlerRef";


type ScriptDetails = {
    [key: string]: {
        [key: string]: {
            controler: string;
            args: any;
            default: any;
        };
    };
}

type DetailsProps = {
    path: string;
    selected: string;
};

export function DetailsPanel({ path, selected }: DetailsProps) {
    console.log('DetailsPanel', path, selected);
    async function queryDetails(): Promise<ScriptDetails> {
        console.log('queryDetails', path, selected);
        let response = await fetch('/api/prepare?' + new URLSearchParams({
            script_path: path,
            callable: selected,
        }), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                params: {}
            })
        });
        if (!response.ok) {
            throw new Error('Failed to fetch script details');
        }
        let data = await response.json() as ScriptDetails;
        console.log('Details', data);
        return data;
    }
    const state = useAsync(queryDetails);

    function renderControlers(details: ScriptDetails) {
        return Object.entries(details).map(([section, controls]) => (
            <Section 
                key={section} 
                title={section} 
                collapsible={true} 
                collapseProps={{ defaultIsOpen: true }}
            >
                {Object.entries(controls).map(([name, control]) => (
                    <SectionCard key={name}>
                        <ControlerRef
                            name={name}
                            type={control.controler}
                            params={control.args}
                            default={control.default}
                        />
                    </SectionCard>
                ))}
            </Section>
        ));
    }

    function render(value: ScriptDetails) {
        return <div>
            <h3>Details</h3>
            {renderControlers(value)}
        </div>
    }

    return state.loading ? <p>Loading...</p> :
        state.error ? <p>Error: {state.error.message}</p> :
            render(state.value ?? {});
}