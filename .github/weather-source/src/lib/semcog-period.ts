/** Monthly archive names encode YYMM; annual index names encode YYYY. */
export function semcogPeriod(url: string) {
  const match = url.match(/\/semcog\/sem\/(maps|daily|hourly)\/(\d{4})\/(?:sem)?(\d{2})(0[1-9]|1[0-2])(?=[a-z.])/);
  return match && match[3] === match[2].slice(-2) ? match : null;
}
