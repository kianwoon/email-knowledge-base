let testStr = 'kb_889d6834.y5-lxY';
console.log(testStr);
const preview = testStr.match(/^([^.]+\.[^.]{3}).*?([^.]{3})$/)?.[0] || testStr;
console.log('Preview:', preview);
const secondPart = testStr.split('.')[1];
console.log('Second part:', secondPart);
