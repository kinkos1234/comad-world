import prompts from 'prompts';
import pc from 'picocolors';
import { PRESETS, SCOPES } from '../presets.mjs';

function onCancel() {
  console.log(`\n${pc.red('Cancelled.')}`);
  process.exit(1);
}

export async function selectOptions() {
  console.log();

  const res1 = await prompts(
    {
      type: 'text',
      name: 'projectName',
      message: 'Project name',
      initial: 'comad-world',
      validate: (v) => (v.trim() ? true : 'Name cannot be empty'),
    },
    { onCancel }
  );
  if (!res1.projectName) onCancel();

  const res2 = await prompts(
    {
      type: 'select',
      name: 'preset',
      message: 'Domain preset',
      choices: PRESETS.map((p) => ({
        title: `${p.title}  ${pc.dim(p.description)}`,
        value: p.value,
      })),
      initial: 0,
    },
    { onCancel }
  );
  if (res2.preset === undefined) onCancel();

  const res3 = await prompts(
    {
      type: 'select',
      name: 'scope',
      message: 'Install scope',
      choices: SCOPES.map((s) => ({
        title: `${s.title}  ${pc.dim(s.description)}`,
        value: s.value,
      })),
      initial: 0,
    },
    { onCancel }
  );
  if (res3.scope === undefined) onCancel();

  return { projectName: res1.projectName.trim(), preset: res2.preset, scope: res3.scope };
}
