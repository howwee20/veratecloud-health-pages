import {describe, it, expect} from 'vitest';
import {dailyTemperatures, temperatureCsv} from '../../src/lib/daily-temperatures';
import {reportsByStation} from '../../src/lib/station';
import {stationDetails} from '../../src/lib/data';

describe('daily temperature alternative', () => {
  it('retains every station and only the values from its latest dated daily row', () => {
    expect(dailyTemperatures.length).toBe(Object.keys(stationDetails).length);
    for (const summary of dailyTemperatures) {
      const rows=reportsByStation[summary.id].daily.rows;
      const lastDate=rows.map(r=>r.isoDate).sort().at(-1);
      const source=rows.find(r=>r.isoDate===lastDate);
      expect(summary.date).toBe(lastDate || 'Unavailable');
      expect(summary.maximum).toBe(source?.cells.airMax.raw || 'Unavailable');
      expect(summary.minimum).toBe(source?.cells.airMin.raw || 'Unavailable');
    }
  });
  it('preserves missing values and dates in the downloadable data', () => {
    expect(temperatureCsv.split('\r\n').length).toBe(dailyTemperatures.length+2);
    for(const row of dailyTemperatures) {
      expect(temperatureCsv).toContain(`"${row.id}","${row.date}","${row.maximum}","${row.minimum}"`);
    }
  });
});
