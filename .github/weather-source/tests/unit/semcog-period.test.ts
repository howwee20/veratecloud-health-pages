import {describe, expect, it} from 'vitest';
import {semcogPeriod} from '../../src/lib/semcog-period';

describe('SEMCOG archive periods', () => {
  it('keeps annual indexes separate from monthly reports', () => {
    for (let year = 1998; year <= 2003; year++) {
      expect(semcogPeriod(`https://climate.geo.msu.edu/semcog/sem/maps/${year}/${year}.html`)).toBeNull();
    }
  });
  it('recognizes valid month names and rejects inconsistent years', () => {
    expect(semcogPeriod('https://climate.geo.msu.edu/semcog/sem/maps/1998/sem9801.gif')?.slice(1)).toEqual(['maps','1998','98','01']);
    expect(semcogPeriod('https://climate.geo.msu.edu/semcog/sem/daily/1998/9812smry.txt')?.slice(1)).toEqual(['daily','1998','98','12']);
    expect(semcogPeriod('https://climate.geo.msu.edu/semcog/sem/hourly/1998/9800hrly.txt')).toBeNull();
    expect(semcogPeriod('https://climate.geo.msu.edu/semcog/sem/hourly/1998/9712hrly.txt')).toBeNull();
  });
});
